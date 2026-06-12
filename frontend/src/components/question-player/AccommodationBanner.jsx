import React from "react";
import Icon from "../Icon";

// First-question accommodations banner — extracted verbatim from
// QuestionPlayer.jsx (CQ wave 6 split). The render guard
// (studentAccommodation && !isReducedDistractions && currentIndex === 0)
// moved inside as an early return, per house precedent.
export default function AccommodationBanner({
  studentAccommodation,
  isReducedDistractions,
  currentIndex,
  theme,
}) {
  if (!(studentAccommodation && !isReducedDistractions && currentIndex === 0)) return null;

  var subtextColor = theme.subtextColor;
  var accomBg = theme.accomBg;
  var accomBorder = theme.accomBorder;

  return (
    <div style={{ maxWidth: "700px", margin: "20px auto 0", padding: "0 20px" }}>
      <div style={{
        background: accomBg,
        border: "1px solid " + accomBorder,
        borderRadius: "10px",
        padding: "15px 20px",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "10px" }}>
          <Icon name="ClipboardList" size={20} />
          <strong style={{ color: "#60a5fa" }}>Your Accommodations</strong>
        </div>
        {studentAccommodation.presets && studentAccommodation.presets.length > 0 && (
          <ul style={{ margin: "0 0 10px 20px", padding: 0, color: "rgba(255,255,255,0.8)", fontSize: "0.95rem" }}>
            {studentAccommodation.presets.map(function(preset, idx) {
              var names = {
                simplified_language: "Simplified Language",
                effort_focused: "Effort-Focused Feedback",
                extra_encouragement: "Extra Encouragement",
                chunked_feedback: "Chunked Feedback",
                modified_expectations: "Modified Expectations",
                visual_structure: "Visual Structure",
                read_aloud_friendly: "Read-Aloud Friendly",
                growth_mindset: "Growth Mindset",
                ell_support: "ELL Support",
                extended_time_1_5x: "Extended Time (1.5x)",
                extended_time_2x: "Extended Time (2x)",
                extended_time_unlimited: "Extended Time (Unlimited)",
                large_text: "Large Text",
                read_aloud: "Read Aloud",
                reduced_distractions: "Reduced Distractions",
              };
              return <li key={idx} style={{ marginBottom: "5px" }}>{names[preset] || preset.replace(/_/g, " ")}</li>;
            })}
          </ul>
        )}
        {studentAccommodation.custom_notes && (
          <p style={{ margin: 0, color: subtextColor, fontSize: "0.9rem", fontStyle: "italic" }}>
            {studentAccommodation.custom_notes}
          </p>
        )}
      </div>
    </div>
  );
}
