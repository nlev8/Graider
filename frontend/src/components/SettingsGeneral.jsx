import React from "react";
import TeacherProfileSection from "./settings-general/TeacherProfileSection";
import AdminAccessSection from "./settings-general/AdminAccessSection";
import GradebookIntegrationSection from "./settings-general/GradebookIntegrationSection";
import NotificationsSection from "./settings-general/NotificationsSection";
import SetupWizardSection from "./settings-general/SetupWizardSection";

export default function SettingsGeneral(props) {
  return (
              <div data-tutorial="settings-general">

            {/* Teacher & School Info + State/Grade/Subject + Email Signature */}
            <TeacherProfileSection {...props} />

            {/* Admin Access */}
            <AdminAccessSection {...props} />

            {/* Gradebook / SIS Integration */}
            <GradebookIntegrationSection {...props} />

            {/* Notifications */}
            <NotificationsSection {...props} />

            {/* Setup Wizard */}
            <SetupWizardSection {...props} />
              </div>
  );
}
