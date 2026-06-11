import React from "react";
import Icon from "./Icon";
import CleverSyncSection from "./settings-classroom/CleverSyncSection";
import OneRosterSection from "./settings-classroom/OneRosterSection";
import LtiSection from "./settings-classroom/LtiSection";
import ScreenshotAddSection from "./settings-classroom/ScreenshotAddSection";
import PeriodsSection from "./settings-classroom/PeriodsSection";
import AccommodationsSection from "./settings-classroom/AccommodationsSection";
import ParentContactsSection from "./settings-classroom/ParentContactsSection";

export default function SettingsClassroom(props) {
  const { isCleverUser, showManualSetup, setShowManualSetup } = props;
  return (
              <>

            {/* Clever Roster Sync Section — shown for Clever SSO users */}
            <CleverSyncSection {...props} />

            {/* OneRoster Integration Section */}
            <OneRosterSection {...props} />

            {/* LTI 1.3 Integration Section — always visible, not a roster provider */}
            <LtiSection {...props} />

            {/* Manual Setup toggle for Clever users */}
            {isCleverUser && (
              <div style={{ marginTop: "10px" }}>
                <button
                  onClick={function() { setShowManualSetup(function(p) { return !p; }); }}
                  style={{
                    background: "none", border: "none", cursor: "pointer",
                    color: "var(--text-muted)", fontSize: "0.82rem",
                    display: "flex", alignItems: "center", gap: "6px", padding: "4px 0",
                  }}
                >
                  <Icon name={showManualSetup ? "ChevronUp" : "ChevronDown"} size={14} />
                  {showManualSetup ? "Hide" : "Show"} Manual Setup (CSV upload, Focus import)
                </button>
              </div>
            )}

            {/* Manual setup sections — always shown for non-Clever users, collapsible for Clever users */}
            {(!isCleverUser || showManualSetup) && (
              <>
            {/* Add Student from Screenshot Section */}
            <ScreenshotAddSection {...props} />

            {/* Period/Class Upload Section */}
            <PeriodsSection {...props} />
              </>
            )}

            {/* IEP/504 Accommodations Section */}
            <AccommodationsSection {...props} />

            {/* Parent Contacts Upload */}
            <ParentContactsSection {...props} />
              </>
  );
}
