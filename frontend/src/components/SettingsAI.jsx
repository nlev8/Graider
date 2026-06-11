import React from "react";
import ModelSelectionSection from "./settings-ai/ModelSelectionSection";
import ExtractionModeSection from "./settings-ai/ExtractionModeSection";
import EnsembleGradingSection from "./settings-ai/EnsembleGradingSection";
import GlobalInstructionsSection from "./settings-ai/GlobalInstructionsSection";
import ApiKeysSection from "./settings-ai/ApiKeysSection";
import AssistantModelSection from "./settings-ai/AssistantModelSection";
import AssistantVoiceSection from "./settings-ai/AssistantVoiceSection";

export default function SettingsAI(props) {
  return (
              <>
            {/* AI Model Selection */}
            <div data-tutorial="settings-ai">
              <ModelSelectionSection {...props} />

              {/* Extraction Mode Toggle - A/B Test */}
              <ExtractionModeSection {...props} />

              {/* Ensemble Grading Toggle */}
              <EnsembleGradingSection {...props} />
            </div>

            {/* Global AI Instructions */}
            <GlobalInstructionsSection {...props} />

            {/* API Keys Section */}
            <ApiKeysSection {...props} />

            {/* Assistant Model Selection */}
            <AssistantModelSection {...props} />

            {/* Assistant Voice Selection */}
            <AssistantVoiceSection {...props} />

              </>
  );
}
